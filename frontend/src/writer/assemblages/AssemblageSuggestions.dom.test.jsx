import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AssemblageSuggestions from './AssemblageSuggestions';
import { writerService } from '../writerService';

/**
 * Semant Writer · W4 — the suggestion feed, mounted.
 *
 * The backend suite owns detection. This owns the surface's half of the division: that the
 * EVIDENCE is shown and is the actual cited records, that the strawman is presented as an
 * editable draft labelled with where it came from, that nothing commits until the author
 * types an intent and presses the button — and that this component cannot reach the canon.
 */

const SUGGESTION = {
  id: 'asm_abc123',
  members: [
    { name: 'interiority', version: 2, definition: 'what the body knows', rendering_intent: 'body first' },
    { name: 'threshold', version: 1, definition: 'a crossing noticed late', rendering_intent: 'one held moment' },
    { name: 'hush', version: 1, definition: 'the sound that stops', rendering_intent: 'quiet' },
  ],
  support: 4,
  evidence: {
    block_count: 4,
    blocks: [
      { run_id: 'wrun_aaa', at: '2026-08-05T10:00:00', directives: ['/ interiority', '/ threshold'], event_ids: ['wu_1'] },
      { run_id: 'wrun_bbb', at: '2026-08-05T11:00:00', directives: ['/ hush'], event_ids: ['wu_2'] },
      { run_id: 'wrun_ccc', at: '2026-08-05T12:00:00', directives: ['/ interiority'], event_ids: ['wu_3'] },
      { run_id: 'wrun_ddd', at: '2026-08-05T13:00:00', directives: ['/ threshold'], event_ids: ['wu_4'] },
    ],
    blocks_with_pulled_operators: 1,
    threshold: 3,
  },
  strawman: {
    name: 'interiority_threshold_hush',
    rendering_intent: 'interiority: body first; threshold: one held moment; hush: quiet',
    source: "composed from the members' own definitions — rewrite it in your words",
  },
};

let container, root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  vi.spyOn(writerService, 'assemblageSuggestions').mockResolvedValue({
    suggestions: [SUGGESTION], threshold: 3, default_threshold: 3,
  });
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(props = {}) {
  await act(async () => {
    root.render(<AssemblageSuggestions projectId="ms_1" {...props} />);
  });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const buttonWithText = (t) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent.trim() === t);

function typeInto(el, value) {
  const proto = el.tagName === 'TEXTAREA'
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('the suggestion cites its evidence', () => {
  it('leads with the block count, not with a claim about meaning', async () => {
    await mount();
    const evidence = byTestId('assemblage-evidence').textContent;
    expect(evidence).toContain('recurred together');
    expect(evidence).toContain('4');
  });

  it('shows the actual blocks it rests on, on request', async () => {
    await mount();
    expect(byTestId('evidence-blocks')).toBeNull();
    await act(async () => { byTestId('show-evidence').click(); });

    const blocks = byTestId('evidence-blocks').textContent;
    for (const b of SUGGESTION.evidence.blocks) {
      expect(blocks).toContain(b.run_id);
    }
    expect(blocks).toContain('/ interiority');
  });

  it('names the members with their versions', async () => {
    await mount();
    const head = byTestId('assemblage-card').textContent;
    expect(head).toContain('interiority');
    expect(head).toContain('v2');
    expect(head).toContain('hush');
  });

  it('reports pulled operators as an aside, not as part of the count', async () => {
    await mount();
    const evidence = byTestId('assemblage-evidence').textContent;
    expect(evidence).toContain('requires');
    // the headline number is still the block count
    expect(evidence).toMatch(/recurred together in\s*4\s*blocks/);
  });

  it('says nothing rather than inventing a pattern when there is none', async () => {
    writerService.assemblageSuggestions.mockResolvedValue({ suggestions: [], threshold: 3 });
    await mount();
    expect(byTestId('assemblage-empty').textContent).toContain('reads what you have actually written');
    expect(byTestId('assemblage-card')).toBeNull();
  });
});

describe('nothing commits until the author names it', () => {
  it('offers the strawman as an editable draft, labelled with where it came from', async () => {
    const create = vi.spyOn(writerService, 'createAssemblage').mockResolvedValue({});
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });

    const naming = byTestId('assemblage-naming');
    expect(naming.textContent).toContain('in your words');
    expect(naming.textContent).toContain("composed from the members' own definitions");
    expect(container.querySelector(`#asm-intent-${SUGGESTION.id}`).value)
      .toBe(SUGGESTION.strawman.rendering_intent);
    expect(create).not.toHaveBeenCalled();
  });

  it('commits only on the explicit action, with the author edited intent', async () => {
    const create = vi.spyOn(writerService, 'createAssemblage').mockResolvedValue({});
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });

    await act(async () => {
      typeInto(container.querySelector(`#asm-name-${SUGGESTION.id}`), 'the_held_crossing');
      typeInto(
        container.querySelector(`#asm-intent-${SUGGESTION.id}`),
        'the body arrives before the mind does, and the room goes quiet',
      );
      typeInto(
        container.querySelector(`#asm-definition-${SUGGESTION.id}`),
        'the crossing she notices only once the room has gone quiet behind her',
      );
    });
    await act(async () => { byTestId('commit-assemblage').click(); });

    expect(create).toHaveBeenCalledWith('ms_1', {
      name: 'the_held_crossing',
      members: ['interiority', 'threshold', 'hush'],
      rendering_intent: 'the body arrives before the mind does, and the room goes quiet',
      definition: 'the crossing she notices only once the room has gone quiet behind her',
    });
  });

  it('leaves the DEFINITION blank, because that field must be the author own', async () => {
    // The strawman seeds the intent only. Pre-filling the definition with the same
    // sentence is what made W4's live gate hand the intent back as the passage.
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });
    expect(container.querySelector(`#asm-intent-${SUGGESTION.id}`).value)
      .toBe(SUGGESTION.strawman.rendering_intent);
    expect(container.querySelector(`#asm-definition-${SUGGESTION.id}`).value).toBe('');
  });

  it('will not commit an assemblage that says the same thing twice', async () => {
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });
    await act(async () => {
      typeInto(container.querySelector(`#asm-name-${SUGGESTION.id}`), 'echo');
      typeInto(container.querySelector(`#asm-intent-${SUGGESTION.id}`), 'the same sentence');
      typeInto(container.querySelector(`#asm-definition-${SUGGESTION.id}`), 'the same sentence');
    });
    expect(byTestId('commit-assemblage').disabled).toBe(true);
  });

  it('will not commit an assemblage with no definition', async () => {
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });
    await act(async () => {
      typeInto(container.querySelector(`#asm-name-${SUGGESTION.id}`), 'x');
      typeInto(container.querySelector(`#asm-intent-${SUGGESTION.id}`), 'mine');
    });
    expect(byTestId('commit-assemblage').disabled).toBe(true);
  });

  it('will not commit an assemblage with no intent of the author own', async () => {
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });
    await act(async () => {
      typeInto(container.querySelector(`#asm-intent-${SUGGESTION.id}`), '   ');
    });
    expect(byTestId('commit-assemblage').disabled).toBe(true);
  });

  it('dismisses without touching the ontology', async () => {
    const dismiss = vi.spyOn(writerService, 'dismissAssemblage').mockResolvedValue({});
    const create = vi.spyOn(writerService, 'createAssemblage');
    await mount();
    await act(async () => { byTestId('dismiss-assemblage').click(); });

    expect(dismiss).toHaveBeenCalledWith('ms_1', ['interiority', 'threshold', 'hush'], 4);
    expect(create).not.toHaveBeenCalled();
  });

  it('says plainly that looking changes nothing', async () => {
    await mount();
    expect(byTestId('assemblage-card').textContent).toContain('Nothing changes until you name it');
  });
});

describe('the feed has no route to the canon', () => {
  it('never calls accept, run, or a scene path', async () => {
    const accept = vi.spyOn(writerService, 'accept');
    const runBlock = vi.spyOn(writerService, 'run');
    await mount();
    await act(async () => { byTestId('show-evidence').click(); });
    expect(accept).not.toHaveBeenCalled();
    expect(runBlock).not.toHaveBeenCalled();
  });

  it('surfaces a server refusal rather than swallowing it', async () => {
    vi.spyOn(writerService, 'createAssemblage')
      .mockRejectedValue(new Error('`like Tolstoy` is not an operator in this project'));
    await mount();
    await act(async () => { byTestId('name-assemblage').click(); });
    await act(async () => {
      typeInto(container.querySelector(`#asm-name-${SUGGESTION.id}`), 'x');
      typeInto(container.querySelector(`#asm-intent-${SUGGESTION.id}`), 'mine');
      typeInto(container.querySelector(`#asm-definition-${SUGGESTION.id}`), 'what it is');
    });
    await act(async () => { byTestId('commit-assemblage').click(); });

    expect(byTestId('assemblage-error').textContent).toContain('not an operator');
  });
});
