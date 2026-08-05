import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import WriterStudio from './WriterStudio';
import { writerService } from './writerService';

/**
 * Semant Writer · W2 — the studio shell.
 *
 * W1 tested this file as the whole surface (a textarea and a results list). W2 moved every
 * decision about a passage INLINE into the editor, so those assertions moved with it and now
 * live in `WriterEditor.dom.test.jsx`, where they run against the real document model.
 *
 * What is left here is what belongs beside the page rather than on it: the author's ontology,
 * and the `#create` gesture that grows it — propose, the author confirms, then store.
 */

const OPERATORS = [
  { id: 'op_1', name: 'threshold', version: 1, definition: 'a crossing noticed late' },
];

let container, root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  vi.spyOn(writerService, 'listOperators').mockResolvedValue(OPERATORS);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(props = {}) {
  await act(async () => {
    root.render(<WriterStudio projectId="ms_1" manuscriptId="ms_1" sceneId="sc_1" {...props} />);
  });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const buttonWithText = (text) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent.trim() === text);

function typeInto(el, value) {
  const proto = el.tagName === 'TEXTAREA'
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('WriterStudio — the shell', () => {
  it('lists the author ontology beside the page', async () => {
    await mount();
    const panel = byTestId('ontology-panel');
    expect(panel.textContent).toContain('threshold');
    expect(panel.textContent).toContain('v1');
    expect(panel.textContent).toContain('a crossing noticed late');
  });

  it('hosts the editor rather than a form', async () => {
    await mount();
    expect(byTestId('writer-prose')).not.toBeNull();
    expect(byTestId('render-button')).not.toBeNull();
    // the W1 textarea surface is gone; prose is written in the editor now
    expect(container.querySelector('#writer-block-input')).toBeNull();
  });

  it('says what an operator is when there are none yet', async () => {
    writerService.listOperators.mockResolvedValue([]);
    await mount();
    expect(byTestId('ontology-panel').textContent).toContain('your word for a thing your prose does');
  });

  it('#create stores only after the author confirms', async () => {
    const create = vi.spyOn(writerService, 'createOperator').mockResolvedValue({});
    await mount();

    await act(async () => { byTestId('create-operator').click(); });
    expect(create).not.toHaveBeenCalled();

    await act(async () => {
      typeInto(container.querySelector('input[aria-label="operator name"]'), 'interiority');
      typeInto(
        container.querySelector('textarea[aria-label="operator definition"]'),
        'what the body knows before the mind admits it',
      );
    });
    await act(async () => { buttonWithText('Add to my operators').click(); });

    expect(create).toHaveBeenCalledWith('ms_1', {
      name: 'interiority',
      definition: 'what the body knows before the mind admits it',
    });
  });

  it('will not store an operator with no definition', async () => {
    await mount();
    await act(async () => { byTestId('create-operator').click(); });
    await act(async () => {
      typeInto(container.querySelector('input[aria-label="operator name"]'), 'hollow');
    });
    // an operator with no definition is a style prior with a label on it
    expect(buttonWithText('Add to my operators').disabled).toBe(true);
  });

  it('surfaces a registry error rather than swallowing it', async () => {
    writerService.listOperators.mockRejectedValue(new Error('registry unreachable'));
    await mount();
    expect(container.querySelector('.writer-error').textContent).toContain('registry unreachable');
  });
});
